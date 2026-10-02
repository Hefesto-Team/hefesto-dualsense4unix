"""NO-JOGO-SEM-FALSO-VERDE-01/T5 (a E2 da MESA-CHEIA-07) — a cor do painel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("a cor do painel da aba No jogo")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip("gi.repository.Gtk", reason="precisa da typelib Gtk")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.widgets import painel_no_jogo as pnj_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    LADO_DO_SWATCH,
    accent_do_card,
    cor_do_swatch,
)
from hefesto_dualsense4unix.app.widgets.painel_no_jogo import PainelNoJogo

_janelas_vivas: list[Any] = []

_ROXO = (128, 0, 255)


def _entry(indice: int, rgb: Any, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "index": indice,
        "connected": True,
        "transport": "usb",
        "is_primary": indice == 0,
        "player": indice + 1,
        "player_slot": indice + 1,
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_rgb": list(rgb) if rgb is not None else None,
    }
    entry.update(extra)
    return entry


def _estado(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "controllers": [dict(e) for e in entries],
        "rumble_ff": {
            "per_vpad": [
                {"player": e["player"], "visto_ha_s": {"touchpad_click": 0.5}}
                for e in entries
            ]
        },
    }


def _painel(entry: dict[str, Any], state: dict[str, Any]) -> PainelNoJogo:
    painel = PainelNoJogo()
    janela = Gtk.OffscreenWindow()
    janela.add(painel)
    janela.show_all()
    _janelas_vivas.append(janela)
    painel.atualizar(entry, state)
    return painel


def test_a_cor_do_painel_e_a_mesma_do_card_byte_a_byte() -> None:
    """A asserção é de identidade, e é a razão de a função ser importada."""
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb == cor_do_swatch(entry)
    assert painel._swatch_rgb == _ROXO


def test_o_swatch_mostra_a_cor_crua_e_nao_a_ajustada() -> None:
    """D8 em uma asserção: o quadradinho é identidade, o traço é legibilidade."""
    entry = _entry(0, _ROXO)
    state = _estado([entry])

    painel = _painel(entry, state)

    assert accent_do_card(entry, state) != _ROXO, (
        "o caso de borda perdeu a graça: escolha uma cor cujo ajuste de "
        "contraste mude os bytes, senão esta régua não distingue as duas"
    )
    assert painel._swatch_rgb == _ROXO


@pytest.mark.parametrize(
    "bruto",
    [
        pytest.param([1, 2], id="dois-canais"),
        pytest.param([0, 0, 0, 0], id="quatro-canais"),
        pytest.param(["ff", 0, 0], id="canal-em-texto"),
        pytest.param({"r": 1, "g": 2, "b": 3}, id="dicionario"),
        pytest.param("azul", id="nome-da-cor"),
    ],
)
def test_o_payload_torto_cai_no_mesmo_lugar_nas_duas_abas(bruto: Any) -> None:
    """O primeiro caso de borda — é aqui que uma cópia diverge, não no feliz."""
    entry = _entry(0, None)
    entry["lightbar_rgb"] = bruto

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb == cor_do_swatch(entry)
    assert painel._swatch_rgb is None


def test_o_painel_nao_tem_leitura_de_cor_propria() -> None:
    """A contraprova estrutural da mordida 1, no fonte."""
    texto = Path(pnj_mod.__file__).read_text(encoding="utf-8")

    assert "lightbar_rgb" not in texto
    assert "cor_do_swatch" in texto


def test_quatro_controles_quatro_cores() -> None:
    """O defeito inteiro, na forma em que ele aparece: a mesa cheia."""
    entries = [
        _entry(0, (0, 0, 255)),
        _entry(1, (255, 0, 0)),
        _entry(2, (0, 255, 0)),
        _entry(3, (255, 0, 128)),
    ]
    state = _estado(entries)

    cores = [_painel(e, state)._swatch_rgb for e in entries]

    assert cores == [(0, 0, 255), (255, 0, 0), (0, 255, 0), (255, 0, 128)]
    assert len(set(cores)) == 4


def test_sem_cor_conhecida_o_quadradinho_fica_vazio() -> None:
    """Sem leitura da lightbar, ``None`` — e o desenho vira só o contorno."""
    entry = _entry(0, None)

    painel = _painel(entry, _estado([entry]))

    assert painel._swatch_rgb is None


def test_trocar_so_a_cor_repinta_o_quadradinho() -> None:
    """A metade que se esquece: a cor tem de estar na ASSINATURA do diff."""
    entry = _entry(0, (0, 0, 255))
    painel = _painel(entry, _estado([entry]))
    assert painel._swatch_rgb == (0, 0, 255)

    novo = _entry(0, (255, 0, 0))
    painel.atualizar(novo, _estado([novo]))

    assert painel._swatch_rgb == (255, 0, 0)


def test_o_titulo_continua_o_mesmo_do_card() -> None:
    """O cabeçalho virou um `Gtk.Box`, e o título tinha de sobreviver a isso."""
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    assert painel._titulo_label.get_text() == pnj_mod.titulo_do_painel(entry)
    assert painel._titulo_label.get_text() != ""


def test_o_quadradinho_tem_o_mesmo_lado_do_card() -> None:
    """Mesmo elemento, mesmo tamanho — e o número tem um dono só."""
    entry = _entry(0, _ROXO)

    painel = _painel(entry, _estado([entry]))

    largura, altura = painel._swatch.get_size_request()
    assert (largura, altura) == (LADO_DO_SWATCH, LADO_DO_SWATCH)
