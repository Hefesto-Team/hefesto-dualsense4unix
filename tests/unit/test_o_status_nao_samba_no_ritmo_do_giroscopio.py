"""NAO-DANCA-01 — a aba Status parou de sambar no ritmo do giroscópio."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o status não samba")

from collections.abc import Iterator
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
_gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app.constants import GUI_DIR
from hefesto_dualsense4unix.app.theme import (
    ESCALA_PADRAO,
    escalar_css,
    escalar_nome_da_fonte,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    ControllerCard,
    frase_mais_longa_do_que_chega_ao_jogo,
    resumo_do_que_chega_ao_jogo,
)


def _gtk_pronto() -> bool:
    try:
        return bool(Gtk.init_check()[0])
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gtk_pronto(), reason="sem GTK/display utilizável"
)

LARGURA_DA_TELA_DELA = 1920

CLASSE_DA_JANELA = "hefesto-dualsense4unix-window"

_janelas_vivas: list[Any] = []

_ENTRY: dict[str, Any] = {
    "index": 0,
    "connected": True,
    "transport": "usb",
    "is_primary": True,
    "uniq": "aa:bb:cc:00:00:01",
    "battery_pct": 100,
    "player": 1,
    "player_slot": 1,
    "lightbar_rgb": [255, 121, 198],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "inputs": {
        "l2": 200,
        "r2": 40,
        "lx": 60,
        "ly": 200,
        "rx": 180,
        "ry": 90,
        "gyro": {"x": 143.2, "y": -412.0, "z": 22.8},
    },
    "vpad_backend": "uhid",
    "vpad_motivo": None,
}


def _estado(item: dict[str, Any]) -> dict[str, Any]:
    """Um `state_full` com UM vpad, o do jogador 1."""
    return {
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "rumble_ff": {"per_vpad": [dict(item, player=1, backend="uhid")]},
    }


def _estado_das_fotos_dela(hz: float) -> dict[str, Any]:
    """O estado das três capturas: giroscópio chegando, três recursos parados."""
    return _estado(
        {
            "motion_streaming": True,
            "motion_hz": hz,
            "motion_forwards": 48210,
            "touchpad_pressionado": False,
            "visto_ha_s": {
                "rumble": 20.0,
                "lightbar": 20.0,
                "audio_do_jogo": 20.0,
            },
        }
    )


ESTADO_FRASE_CURTA = _estado(
    {
        "motion_streaming": True,
        "motion_forwards": 48210,
        "touchpad_pressionado": False,
        "visto_ha_s": {
            "rumble": 0.4,
            "lightbar": 0.4,
            "trigger": 0.4,
            "touchpad_click": 0.4,
            "audio_do_jogo": 0.4,
        },
    }
)

ESTADO_FRASE_LONGA = _estado(
    {
        "motion_streaming": True,
        "motion_hz": 1000.0,
        "motion_forwards": 48210,
        "touchpad_pressionado": False,
        "rumble_no_fisico": [255, 255],
        "rumble_no_fisico_ha_s": 0.4,
        "visto_ha_s": {"rumble": 0.4, "lightbar": 20.0, "trigger": 20.0},
    }
)


@pytest.fixture(autouse=True, scope="module")
def _tema_na_escala_que_sai() -> Iterator[None]:
    """Aplica o tema pelos DOIS canais de `app.theme.apply_theme`, e desfaz."""

    delta = ESCALA_PADRAO
    tela = Gdk.Screen.get_default()
    provider = Gtk.CssProvider()
    bruto = (GUI_DIR / "theme.css").read_text(encoding="utf-8")
    provider.load_from_data(escalar_css(bruto, delta).encode("utf-8"))
    if tela is not None:
        Gtk.StyleContext.add_provider_for_screen(
            tela, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    anterior = None
    if settings is not None and delta:
        anterior = settings.get_property("gtk-font-name")
        settings.set_property(
            "gtk-font-name", escalar_nome_da_fonte(anterior or "", delta)
        )
    yield
    if settings is not None and anterior is not None:
        settings.set_property("gtk-font-name", anterior)
    if tela is not None:
        Gtk.StyleContext.remove_provider_for_screen(tela, provider)


def _assentar(vezes: int = 8) -> None:
    """Drena o laço mais de uma vez: widget sem alocação mede 1x1."""
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


BLOCOS_ABAIXO = (
    "_gyro_box",
    "_miolo_inferior",
    "_lightbar_box",
    "_mic_box",
    "_speaker_box",
)


def _geometria(state_global: dict[str, Any]) -> dict[str, int]:
    """Onde cada peça do card cai, com este estado, na tela dela."""
    from hefesto_dualsense4unix.app.mic_monitor import LeituraMic

    card = ControllerCard(compact=False)
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class(CLASSE_DA_JANELA)
    janela.add(card)
    janela.set_size_request(LARGURA_DA_TELA_DELA, 900)
    janela.show_all()
    _janelas_vivas.append(janela)
    card.update(_ENTRY, state_global, LeituraMic(nivel=0.6, muted=False))
    janela.resize(LARGURA_DA_TELA_DELA, 900)
    _assentar()

    medida = {
        "altura da faixa da frase": card._faixa_gyro_bateria.get_allocation().height,
        "altura da frase": card._verdade_label.get_allocation().height,
        "topo da barra de bateria": card._battery_bar.get_allocation().y,
        "topo do rótulo Bateria:": card._battery_row.get_children()[
            0
        ].get_allocation().y,
        "altura que o card pede": card.get_preferred_height()[1],
        "linhas da frase": card._verdade_label.get_layout().get_line_count(),
    }
    for nome in BLOCOS_ABAIXO:
        bloco = getattr(card, nome, None)
        if bloco is not None:
            medida[f"topo de {nome}"] = bloco.get_allocation().y
    return medida


def _o_que_dancou(
    antes: dict[str, int], depois: dict[str, int]
) -> dict[str, int]:
    """Peça → quantos pixels ela se mexeu. Vazio = ninguém dançou."""
    return {
        nome: depois[nome] - antes[nome]
        for nome in antes
        if nome != "linhas da frase" and depois[nome] != antes[nome]
    }


def test_a_frase_mais_longa_e_a_que_a_funcao_dona_monta() -> None:
    """A régua da reserva não é ficção — o produto sabe montar aquela frase.

    Se `frase_mais_longa_do_que_chega_ao_jogo` inventasse um texto que
    `resumo_do_que_chega_ao_jogo` nunca produz, a altura reservada seria um
    número decorativo: grande demais (vão sem causa) ou pequeno demais (a
    dança de volta, num estado que ninguém testou).
    """
    frase = resumo_do_que_chega_ao_jogo(_ENTRY, ESTADO_FRASE_LONGA)
    assert frase == frase_mais_longa_do_que_chega_ao_jogo()


def test_a_frase_mais_longa_nomeia_os_seis_recursos() -> None:
    """Nenhum recurso fica de fora da régua — é o que a torna o TETO."""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        _NOME_NA_FRASE,
    )

    frase = frase_mais_longa_do_que_chega_ao_jogo()
    faltando = [nome for _r, nome in _NOME_NA_FRASE if nome not in frase]
    assert not faltando, f"a régua não menciona {faltando}"
    for prefixo in ("No jogo agora: ", "pararam: ", "sem pedido ainda: "):
        assert prefixo in frase


def test_a_frase_curta_e_a_mais_longa_nao_movem_nada() -> None:
    """**A diferença tem de ser ZERO pixel** — em toda peça do card."""
    curta = _geometria(ESTADO_FRASE_CURTA)
    longa = _geometria(ESTADO_FRASE_LONGA)

    assert curta["linhas da frase"] != longa["linhas da frase"], (
        "as duas frases ocupam o mesmo número de linhas "
        f"({curta['linhas da frase']}); este teste perdeu os dentes — "
        "a frase curta e a mais longa precisam quebrar diferente"
    )

    dancou = _o_que_dancou(curta, longa)
    assert not dancou, "o card dançou entre a frase curta e a mais longa: " + (
        ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
    )


def test_as_tres_frases_das_fotos_dela_nao_movem_nada() -> None:
    """Os três Hz das capturas de 14:11, medidos um contra o outro."""
    base = _geometria(_estado_das_fotos_dela(160.0))
    for hz in (193.0, 190.0):
        outra = _geometria(_estado_das_fotos_dela(hz))
        dancou = _o_que_dancou(base, outra)
        assert not dancou, (
            f"o card dançou entre ~160 Hz e ~{hz:.0f} Hz: "
            + ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
        )


def test_a_bateria_nao_muda_de_linha_com_o_texto_ao_lado() -> None:
    """A anotação dela: a ``Bateria:`` subia para a linha de cima e voltava."""
    curta = _geometria(ESTADO_FRASE_CURTA)
    longa = _geometria(ESTADO_FRASE_LONGA)
    for peca in ("topo da barra de bateria", "topo do rótulo Bateria:"):
        assert curta[peca] == longa[peca], (
            f"a bateria mudou de linha ({peca}): "
            f"{curta[peca]}px → {longa[peca]}px"
        )


def test_a_reserva_cabe_a_frase_mais_longa_sem_sobrar_linha() -> None:
    """A altura reservada é a do TETO, e não uma folga inventada."""
    longa = _geometria(ESTADO_FRASE_LONGA)
    curta = _geometria(ESTADO_FRASE_CURTA)
    assert curta["altura da frase"] == longa["altura da frase"]
    assert longa["linhas da frase"] >= curta["linhas da frase"]


def test_a_aba_no_jogo_nao_samba_com_o_mesmo_numero() -> None:
    """O outro lugar da janela onde o Hz aparece, medido: 0px de dança."""
    from hefesto_dualsense4unix.app.widgets.painel_no_jogo import (
        RECURSOS,
        PainelNoJogo,
    )

    def _medir(hz: float) -> dict[str, int]:
        painel = PainelNoJogo()
        janela = Gtk.OffscreenWindow()
        janela.get_style_context().add_class(CLASSE_DA_JANELA)
        janela.add(painel)
        janela.set_size_request(900, 400)
        janela.show_all()
        _janelas_vivas.append(janela)
        painel.atualizar(_ENTRY, _estado_das_fotos_dela(hz))
        janela.resize(900, 400)
        _assentar()
        medida = {}
        for recurso in RECURSOS:
            _rotulo, valor = painel._linhas[recurso]
            alocacao = valor.get_allocation()
            medida[f"topo de {recurso}"] = alocacao.y
            medida[f"altura de {recurso}"] = alocacao.height
        return medida

    base = _medir(160.0)
    for hz in (193.0, 190.0, 1000.0):
        outra = _medir(hz)
        dancou = _o_que_dancou(base, outra)
        assert not dancou, (
            f'a aba "No jogo" dançou entre ~160 Hz e ~{hz:.0f} Hz: '
            + ", ".join(f"{nome} {delta:+d}px" for nome, delta in dancou.items())
        )
