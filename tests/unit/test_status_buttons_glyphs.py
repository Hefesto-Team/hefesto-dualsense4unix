"""tests/unit/test_status_buttons_glyphs.py — glyphs/sticks do card por controle.

O redesign UI-STATUS-STICKS-REDESIGN-01 virou parte do ControllerCard no
STATUS-02: a lógica de acender glyphs, o threshold analógico de L2/R2 e o
diff a 10 Hz moram em ``ControllerCard._update_inputs``/``_refresh_glyphs``
(antes eram singletons da mixin de status). Exercita com GTK REAL:

  (a) cross + dpad_up pressionados → set_pressed(True) exatamente nesses dois.
  (b) Nenhum botão pressionado → todos False.
  (c) L2/R2 analógicos: l2_raw > 30 ilumina o glyph l2; <= 30 apaga.
  (d) l3 pressionado → stick esquerdo pressionado; título com o accent.
  (e) r3 pressionado → stick direito pressionado; título com o accent.
  (f) Diff: estado igual ao anterior → set_pressed não é chamado de novo.
  (g) ALL_BUTTONS continua com 16 entradas (grid 4x4).
  (h) reset_inputs apaga todos os glyphs e mostra o "—" (sem leitor).
"""
# ruff: noqa: E402 — gi.require_version precisa vir antes dos imports de gi
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    ALL_BUTTONS,
    L2_R2_THRESHOLD,
    ControllerCard,
)

STATE: dict[str, Any] = {"native_mode": False}


def _entry(**inputs_kw: Any) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
        "l2_raw": 0,
        "r2_raw": 0,
        "buttons": [],
    }
    inputs.update(inputs_kw)
    return {
        "index": 0,
        "connected": True,
        "transport": "usb",
        "is_primary": True,
        "uniq": "aa:bb:cc:00:00:01",
        "battery_pct": 80,
        "player": None,
        "player_slot": 1,
        "lightbar_rgb": [16, 32, 72],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": inputs,
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }


@pytest.fixture()
def card() -> ControllerCard:
    c = ControllerCard(compact=False)
    c.show_all()
    return c


# ---------------------------------------------------------------------------
# (a) cross + dpad_up pressionados
# ---------------------------------------------------------------------------


def test_cross_e_dpad_up_pressionados(card: ControllerCard) -> None:
    """cross e dpad_up acendem; os demais ficam apagados."""
    card.update(_entry(buttons=["cross", "dpad_up"]), STATE)

    assert card._glyphs["cross"].is_pressed
    assert card._glyphs["dpad_up"].is_pressed
    for nome, glyph in card._glyphs.items():
        if nome not in ("cross", "dpad_up", "l2", "r2"):
            assert not glyph.is_pressed, f"{nome} devia estar False"


# ---------------------------------------------------------------------------
# (b) Nenhum botão pressionado
# ---------------------------------------------------------------------------


def test_nenhum_botao_pressionado(card: ControllerCard) -> None:
    card.update(_entry(), STATE)
    for nome, glyph in card._glyphs.items():
        assert not glyph.is_pressed, f"{nome} devia estar False"


# ---------------------------------------------------------------------------
# (c) L2/R2 analógicos por threshold
# ---------------------------------------------------------------------------


def test_l2_raw_acima_threshold_ilumina_glyph(card: ControllerCard) -> None:
    card.update(_entry(l2_raw=L2_R2_THRESHOLD + 1), STATE)
    assert card._glyphs["l2"].is_pressed
    assert not card._glyphs["r2"].is_pressed


def test_l2_raw_abaixo_threshold_apaga_glyph(card: ControllerCard) -> None:
    card.update(_entry(l2_raw=L2_R2_THRESHOLD + 5), STATE)
    assert card._glyphs["l2"].is_pressed

    card.update(_entry(l2_raw=L2_R2_THRESHOLD), STATE)
    assert not card._glyphs["l2"].is_pressed


def test_r2_raw_acima_threshold_ilumina_glyph(card: ControllerCard) -> None:
    card.update(_entry(r2_raw=L2_R2_THRESHOLD + 10), STATE)
    assert card._glyphs["r2"].is_pressed
    assert not card._glyphs["l2"].is_pressed


# ---------------------------------------------------------------------------
# (d) L3 pressionado — stick esquerdo com o accent do controle
# ---------------------------------------------------------------------------


def test_l3_pressionado_pinta_titulo_com_accent(card: ControllerCard) -> None:
    card.update(_entry(buttons=["l3"]), STATE)

    assert card._stick_left._l3_pressed
    assert not card._stick_right._l3_pressed

    markup_esq = card._stick_left_title.get_label()
    assert card._accent_hex in markup_esq  # cor do CONTROLE, não roxo fixo
    markup_dir = card._stick_right_title.get_label()
    assert card._accent_hex not in markup_dir


# ---------------------------------------------------------------------------
# (e) R3 pressionado — stick direito com o accent
# ---------------------------------------------------------------------------


def test_r3_pressionado_pinta_titulo_com_accent(card: ControllerCard) -> None:
    card.update(_entry(buttons=["r3"]), STATE)

    assert card._stick_right._l3_pressed
    assert not card._stick_left._l3_pressed
    assert card._accent_hex in card._stick_right_title.get_label()


# ---------------------------------------------------------------------------
# (f) Diff: estado idêntico não dispara set_pressed novamente
# ---------------------------------------------------------------------------


def test_diff_estado_igual_nao_re_dispara_set_pressed(
    card: ControllerCard,
) -> None:
    chamadas: dict[str, int] = dict.fromkeys(ALL_BUTTONS, 0)

    for nome, glyph in card._glyphs.items():
        original = glyph.set_pressed

        def _espiao(
            val: bool, _nome: str = nome, _orig: Any = original
        ) -> None:
            chamadas[_nome] += 1
            _orig(val)

        glyph.set_pressed = _espiao  # type: ignore[method-assign]

    card.update(_entry(buttons=["circle"]), STATE)
    apos_1 = dict(chamadas)

    card.update(_entry(buttons=["circle"]), STATE)  # mesmo estado
    for nome in ALL_BUTTONS:
        assert apos_1[nome] == chamadas[nome], (
            f"set_pressed chamado novamente em '{nome}' sem mudança de estado"
        )


# ---------------------------------------------------------------------------
# (g) grid tem exatamente 16 entradas (ALL_BUTTONS) e o card os carrega
# ---------------------------------------------------------------------------


def test_all_buttons_tem_16_entradas(card: ControllerCard) -> None:
    assert len(ALL_BUTTONS) == 16, f"Esperado 16, obtido {len(ALL_BUTTONS)}"
    assert sorted(card._glyphs) == sorted(ALL_BUTTONS)


# ---------------------------------------------------------------------------
# (h) reset_inputs apaga todos os glyphs e mostra o "—"
# ---------------------------------------------------------------------------


def test_reset_inputs_apaga_glyphs_e_mostra_sem_leitor(
    card: ControllerCard,
) -> None:
    card.update(
        _entry(buttons=["cross", "triangle"], l2_raw=100, lx=200, ly=60),
        STATE,
    )
    assert card._glyphs["cross"].is_pressed

    card.reset_inputs()

    for nome, glyph in card._glyphs.items():
        assert not glyph.is_pressed, f"{nome} devia estar apagado após reset"
    assert not card._stick_left._l3_pressed
    assert not card._stick_right._l3_pressed
    assert card._sem_leitor_label.get_visible() is True
    assert card._inputs_area.get_visible() is False


# ---------------------------------------------------------------------------
# Alias share/create (BUG-GLYPH-SHARE-NAME-MISMATCH-01) — preservado no card
# ---------------------------------------------------------------------------


def test_daemon_emite_create_e_o_glyph_share_acende(
    card: ControllerCard,
) -> None:
    card.update(_entry(buttons=["create"]), STATE)
    assert card._glyphs["share"].is_pressed
