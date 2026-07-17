"""tests/unit/test_status_cards.py — aba Status por controle (STATUS-02/03 + BT-03).

Exercita com GTK REAL (a suíte roda com display; 0 skips):

  * 2 controles no ``state_full`` → 2 ControllerCard com título e bateria
    PRÓPRIOS ("Controle 1 — BT · Jogador 1" pelo ``player_slot``/``player``;
    fallback ``index + 1`` sem slot; sem "Jogador" fora do co-op — D7);
  * 2 ticks com o MESMO conjunto → os MESMOS objetos de widget (``id()``,
    sem rebuild); conjunto novo → rebuild;
  * inputs do card 2 vêm EXCLUSIVAMENTE de ``controllers[1].inputs``;
  * entrada-placeholder offline (HARM-CARD-FANTASMA-01) e ``uniq`` None não
    criam card fantasma nem colidem;
  * ``inputs is None`` → área de inputs vira "—" (nunca o último valor
    congelado como vivo);
  * rótulos da lightbar pela FONTE (apagada / cor desconhecida / Nativo);
  * badge de degradação (BT-03): acende com uinput+motivo, some com uhid;
    frases leigas nunca cravam o mecanismo do sono BT;
  * glyphs/sticks/barras recebem o accent AJUSTADO (espião nos widgets);
  * gate de timers: NENHUMA ocorrência nova de timeout/idle do GLib em
    relação ao baseline da mixin (o gate é diff, não contagem absoluta).
"""
# ruff: noqa: E402 — gi.require_version precisa vir antes dos imports de gi
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import status_actions as sa_mod
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.widgets import controller_card as cc_mod
from hefesto_dualsense4unix.app.widgets.controller_card import (
    MOTIVOS_DEGRADACAO_LEIGOS,
    rotulo_lightbar,
    texto_degradacao,
    titulo_do_card,
)
from hefesto_dualsense4unix.utils.color_contrast import (
    ACCENT_NEUTRO,
    ensure_min_contrast,
    rgb_para_hex,
)

# Cores de exercício: a medida ao vivo na máquina de referência + 1 distinta.
COR_A = (16, 32, 72)
COR_B = (0, 255, 0)


# ---------------------------------------------------------------------------
# Fakes mínimos (labels/barras do frame Estado) + host com slot REAL
# ---------------------------------------------------------------------------


class _FakeLabel:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.text: str | None = None
        self.visible: bool | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, value: bool) -> None:
        self.visible = value

    def set_fraction(self, _frac: float) -> None:
        pass

    def hide(self) -> None:
        self.visible = False


class _FakeBar(_FakeLabel):
    def __init__(self) -> None:
        super().__init__()
        self.fraction: float | None = None

    def set_fraction(self, frac: float) -> None:
        self.fraction = frac

    def set_show_text(self, _v: bool) -> None:
        pass


class _Builder:
    """Slot dos cards é um GtkBox REAL; o resto são fakes leves."""

    def __init__(self) -> None:
        self._w: dict[str, Any] = {
            "status_players_slot": Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=12
            ),
        }

    def get_object(self, wid: str) -> Any:
        if wid not in self._w:
            self._w[wid] = _FakeBar() if "bar" in wid else _FakeLabel()
        return self._w[wid]


class _Host(StatusActionsMixin):
    def __init__(self) -> None:
        self.builder = _Builder()

    @property
    def slot(self) -> Any:
        return self.builder.get_object("status_players_slot")

    def cards(self) -> list[Any]:
        return list(self.slot.get_children())


@pytest.fixture()
def host(monkeypatch: pytest.MonkeyPatch) -> _Host:
    # Sem popup nos testes — força o caminho de render
    # (BUG-COMBO-POPUP-FLICKER-02 pausa tudo com grab ativo).
    monkeypatch.setattr(
        StatusActionsMixin, "_popup_is_open", staticmethod(lambda: False)
    )
    return _Host()


def _inputs(**valores: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "lx": 128,
        "ly": 128,
        "rx": 128,
        "ry": 128,
        "l2_raw": 0,
        "r2_raw": 0,
        "buttons": [],
    }
    base.update(valores)
    return base


def _entry(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "index": 0,
        "connected": True,
        "transport": "bt",
        "is_primary": True,
        "uniq": "aa:bb:cc:00:00:01",
        "battery_pct": 80,
        "player": None,
        "player_slot": None,
        "lightbar_rgb": list(COR_A),
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "inputs": _inputs(),
        "vpad_backend": "uhid",
        "vpad_motivo": None,
    }
    base.update(kw)
    return base


def _state(*controllers: dict[str, Any], **top: Any) -> dict[str, Any]:
    st: dict[str, Any] = {
        "connected": bool(controllers),
        "transport": "bt",
        "battery_pct": 80,
        "active_profile": "vitoria",
        "native_mode": False,
        "controllers": list(controllers),
    }
    st.update(top)
    return st


# ---------------------------------------------------------------------------
# 2 controles → 2 cards com identidade própria
# ---------------------------------------------------------------------------


def test_dois_controles_criam_dois_cards_com_titulo_e_bateria_proprios(
    host: _Host,
) -> None:
    state = _state(
        _entry(player_slot=1, player=1, battery_pct=80),
        _entry(
            index=1,
            uniq="aa:bb:cc:00:00:02",
            transport="usb",
            is_primary=False,
            player_slot=2,
            player=2,
            battery_pct=55,
        ),
    )
    host._render_live_state(state)

    cards = host.cards()
    assert len(cards) == 2
    assert cards[0]._title_label.get_text() == "Controle 1 — BT · Jogador 1"
    assert cards[1]._title_label.get_text() == "Controle 2 — USB · Jogador 2"
    assert cards[0]._battery_bar.get_text() == "80 %"
    assert cards[1]._battery_bar.get_text() == "55 %"


def test_titulo_fallback_index_mais_um_sem_slot_e_sem_jogador(
    host: _Host,
) -> None:
    """Sem ``player_slot`` o N é index+1; sem ``player`` NÃO inventa jogador (D7)."""
    state = _state(
        _entry(),
        _entry(
            index=1,
            uniq="aa:bb:cc:00:00:02",
            transport="usb",
            is_primary=False,
            player_slot=None,
            player=None,
        ),
    )
    host._render_live_state(state)

    titulo = host.cards()[1]._title_label.get_text()
    assert titulo == "Controle 2 — USB"
    assert "Jogador" not in titulo


def test_titulo_do_card_funcao_pura() -> None:
    assert titulo_do_card(_entry(player_slot=3, player=2)) == (
        "Controle 3 — BT · Jogador 2"
    )
    assert titulo_do_card(_entry(index=1, transport="usb")) == "Controle 2 — USB"
    # bool não é int válido (payload malformado não vira número).
    assert titulo_do_card(_entry(player_slot=True, player=True)).startswith(
        "Controle 1 — BT"
    )


# ---------------------------------------------------------------------------
# Reconstrução SÓ quando o conjunto muda
# ---------------------------------------------------------------------------


def test_mesmo_conjunto_mesmos_objetos_de_widget(host: _Host) -> None:
    state = _state(
        _entry(),
        _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
    )
    host._render_live_state(state)
    ids_1 = [id(c) for c in host.cards()]

    host._render_live_state(state)  # 2º tick com o MESMO conjunto
    ids_2 = [id(c) for c in host.cards()]

    assert ids_1 == ids_2  # sem rebuild


def test_conjunto_novo_reconstroi(host: _Host) -> None:
    host._render_live_state(_state(_entry()))
    assert len(host.cards()) == 1
    id_antes = id(host.cards()[0])

    host._render_live_state(
        _state(
            _entry(),
            _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
        )
    )
    cards = host.cards()
    assert len(cards) == 2
    assert id(cards[0]) != id_antes  # conjunto mudou → rebuild


# ---------------------------------------------------------------------------
# Inputs do card N vêm exclusivamente de controllers[N]
# ---------------------------------------------------------------------------


def test_inputs_do_card_2_vem_exclusivamente_de_controllers_1(
    host: _Host,
) -> None:
    state = _state(
        _entry(inputs=_inputs(l2_raw=200, lx=10)),
        _entry(
            index=1,
            uniq="aa:bb:cc:00:00:02",
            is_primary=False,
            inputs=_inputs(l2_raw=10, lx=250),
        ),
    )
    host._render_live_state(state)

    card_1, card_2 = host.cards()
    assert card_1._l2_bar.get_text() == "200 / 255"
    assert card_1._stick_left._x == 10
    assert card_2._l2_bar.get_text() == "10 / 255"
    assert card_2._stick_left._x == 250


# ---------------------------------------------------------------------------
# Card fantasma: placeholder offline e uniq None
# ---------------------------------------------------------------------------


def test_placeholder_offline_nao_cria_card_fantasma(host: _Host) -> None:
    """HARM-CARD-FANTASMA-01: a entrada com connected=False não vira card."""
    state = _state()  # sem controles conectados
    state["controllers"] = [{"connected": False}]  # o placeholder do daemon
    host._render_live_state(state)
    assert host.cards() == []


def test_uniq_none_nao_cria_fantasma_nem_colide(host: _Host) -> None:
    """Dois controles keyed por path (uniq None) → 2 cards distintos."""
    state = _state(
        _entry(uniq=None),
        _entry(index=1, uniq=None, transport="usb", is_primary=False),
    )
    host._render_live_state(state)
    cards = host.cards()
    assert len(cards) == 2
    assert id(cards[0]) != id(cards[1])
    assert len(host._status_cards) == 2  # chaves não colidiram


# ---------------------------------------------------------------------------
# inputs None → "—" (sem leitor; nunca congela o último valor)
# ---------------------------------------------------------------------------


def test_inputs_none_mostra_travessao(host: _Host) -> None:
    host._render_live_state(_state(_entry(inputs=None)))
    card = host.cards()[0]
    assert card._sem_leitor_label.get_visible() is True
    assert card._sem_leitor_label.get_text() == "—"
    assert card._inputs_area.get_visible() is False


def test_inputs_none_nao_congela_o_ultimo_valor(host: _Host) -> None:
    """Leitor caiu e voltou: o valor antigo não reaparece como vivo."""
    host._render_live_state(_state(_entry(inputs=_inputs(l2_raw=200))))
    card = host.cards()[0]
    assert card._l2_bar.get_text() == "200 / 255"

    host._render_live_state(_state(_entry(inputs=None)))
    assert card._sem_leitor_label.get_visible() is True
    assert card._l2_bar.get_text() == "0 / 255"  # área resetada, não congelada

    host._render_live_state(_state(_entry(inputs=_inputs(l2_raw=0))))
    assert card._sem_leitor_label.get_visible() is False
    assert card._inputs_area.get_visible() is True
    assert card._l2_bar.get_text() == "0 / 255"


def test_reset_live_widgets_vira_sem_leitor_em_todos_os_cards(
    host: _Host,
) -> None:
    """IPC sem resposta (`_reset_live_widgets`): cada card mostra o "—"."""
    host._render_live_state(
        _state(
            _entry(inputs=_inputs(l2_raw=99)),
            _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
        )
    )
    host._reset_live_widgets()
    for card in host.cards():
        assert card._sem_leitor_label.get_visible() is True
        assert card._inputs_area.get_visible() is False


# ---------------------------------------------------------------------------
# Rótulos da lightbar pela FONTE (STATUS-03)
# ---------------------------------------------------------------------------


def test_rotulo_sysfs_apagada(host: _Host) -> None:
    host._render_live_state(
        _state(
            _entry(lightbar_rgb=[0, 0, 0], lightbar_on=False,
                   lightbar_source="sysfs")
        )
    )
    card = host.cards()[0]
    assert card._lightbar_label.get_visible() is True
    assert card._lightbar_label.get_text() == "Lightbar: apagada"
    # Accent neutro AJUSTADO nos traços.
    assert card._accent == ensure_min_contrast(ACCENT_NEUTRO)


def test_rotulo_desconhecida_nunca_diz_apagada(host: _Host) -> None:
    host._render_live_state(
        _state(
            _entry(lightbar_rgb=None, lightbar_on=False,
                   lightbar_source="desconhecida")
        )
    )
    card = host.cards()[0]
    assert card._lightbar_label.get_visible() is True
    assert card._lightbar_label.get_text() == "Lightbar: cor desconhecida"
    assert card._accent == ensure_min_contrast(ACCENT_NEUTRO)


def test_rotulo_nativo_o_jogo_e_dono_do_led(host: _Host) -> None:
    host._render_live_state(_state(_entry(), native_mode=True))
    card = host.cards()[0]
    assert card._lightbar_label.get_visible() is True
    assert card._lightbar_label.get_text() == "em Nativo o jogo é dono do LED"
    # Última cor conhecida segue nos traços (ajustada).
    assert card._accent == ensure_min_contrast(COR_A)


def test_cor_conhecida_e_acesa_sem_rotulo(host: _Host) -> None:
    host._render_live_state(_state(_entry()))
    card = host.cards()[0]
    assert card._lightbar_label.get_visible() is False
    assert card._accent == ensure_min_contrast(COR_A)


@pytest.mark.parametrize(
    ("entry_kw", "state_kw", "esperado"),
    [
        # sysfs + on=False → apagada (escrita foi NOSSA).
        (
            {"lightbar_rgb": [10, 10, 10], "lightbar_on": False,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: apagada",
        ),
        # sysfs + rgb preto → apagada mesmo com on=True defensivo.
        (
            {"lightbar_rgb": [0, 0, 0], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: apagada",
        ),
        # desired preto (nós mandamos apagar por hidraw) → apagada.
        (
            {"lightbar_rgb": [0, 0, 0], "lightbar_on": False,
             "lightbar_source": "desired"},
            {},
            "Lightbar: apagada",
        ),
        # desconhecida → NUNCA "apagada".
        (
            {"lightbar_rgb": None, "lightbar_on": False,
             "lightbar_source": "desconhecida"},
            {},
            "Lightbar: cor desconhecida",
        ),
        # rgb ausente com fonte estranha → desconhecida.
        (
            {"lightbar_rgb": None, "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            "Lightbar: cor desconhecida",
        ),
        # Nativo vence: o jogo é dono do LED.
        (
            {"lightbar_rgb": [16, 32, 72], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {"native_mode": True},
            "em Nativo o jogo é dono do LED",
        ),
        # cor conhecida acesa → sem rótulo.
        (
            {"lightbar_rgb": [16, 32, 72], "lightbar_on": True,
             "lightbar_source": "sysfs"},
            {},
            None,
        ),
    ],
)
def test_rotulo_lightbar_funcao_pura(
    entry_kw: dict[str, Any], state_kw: dict[str, Any], esperado: str | None
) -> None:
    rotulo, _base = rotulo_lightbar(_entry(**entry_kw), _state(**state_kw))
    assert rotulo == esperado


# ---------------------------------------------------------------------------
# Badge de degradação (BT-03)
# ---------------------------------------------------------------------------


def test_badge_degradado_acende_com_uinput_e_motivo_e_some_com_uhid(
    host: _Host,
) -> None:
    state = _state(
        _entry(vpad_backend="uinput", vpad_motivo="uhid_bind_falhou")
    )
    host._render_live_state(state)
    card = host.cards()[0]
    assert card._degradacao_badge.get_visible() is True
    texto = card._degradacao_badge.get_text()
    assert texto.startswith("emulação degradada (uinput): ")
    assert MOTIVOS_DEGRADACAO_LEIGOS["uhid_bind_falhou"] in texto

    # Promovido a uhid → o badge some (mesmo card, sem rebuild).
    host._render_live_state(_state(_entry(vpad_backend="uhid")))
    assert card._degradacao_badge.get_visible() is False


def test_badge_nao_acende_sem_motivo_uinput_por_design(host: _Host) -> None:
    """Máscara xbox é uinput POR DESIGN (motivo None) — não é degradação."""
    host._render_live_state(
        _state(_entry(vpad_backend="uinput", vpad_motivo=None))
    )
    assert host.cards()[0]._degradacao_badge.get_visible() is False


@pytest.mark.parametrize(
    "motivo",
    [
        "uhid_indisponivel",
        "uhid_start_falhou",
        "uhid_bind_falhou",
        "uhid_vetado_pelo_chamador",
        "sem_uhid",
    ],
)
def test_frases_leigas_nunca_cravam_o_mecanismo_do_sono_bt(
    motivo: str,
) -> None:
    """Contrato do BT-03: o texto não atribui causa BT não provada."""
    texto = texto_degradacao(
        _entry(vpad_backend="uinput", vpad_motivo=motivo)
    )
    assert texto is not None
    assert texto.startswith("emulação degradada (uinput): ")
    minusculo = texto.lower()
    for proibido in ("bluetooth", " bt", "sono", "dormiu", "adormec"):
        assert proibido not in minusculo, f"{motivo!r} crava mecanismo: {texto}"
    # Frase leiga: sem o jargão cru do motivo.
    assert "uhid_" not in texto


def test_texto_degradacao_motivo_desconhecido_vira_legivel() -> None:
    texto = texto_degradacao(
        _entry(vpad_backend="uinput", vpad_motivo="motivo_novo_do_daemon")
    )
    assert texto == "emulação degradada (uinput): motivo novo do daemon"


# ---------------------------------------------------------------------------
# Tinting: glyphs/sticks/barras recebem a cor AJUSTADA (espião nos widgets)
# ---------------------------------------------------------------------------


def test_glyphs_e_sticks_recebem_set_accent_com_a_cor_ajustada(
    host: _Host,
) -> None:
    host._render_live_state(_state(_entry(lightbar_rgb=list(COR_A))))
    card = host.cards()[0]

    recebidos: dict[str, Any] = {}
    stick_orig = card._stick_left.set_accent
    glyph = card._glyphs["cross"]
    glyph_orig = glyph.set_accent

    def _espiao_stick(rgb: Any) -> None:
        recebidos["stick"] = rgb
        stick_orig(rgb)

    def _espiao_glyph(rgb: Any) -> None:
        recebidos["glyph"] = rgb
        glyph_orig(rgb)

    card._stick_left.set_accent = _espiao_stick  # type: ignore[method-assign]
    glyph.set_accent = _espiao_glyph  # type: ignore[method-assign]

    host._render_live_state(_state(_entry(lightbar_rgb=list(COR_B))))

    ajustada = ensure_min_contrast(COR_B)
    assert recebidos["stick"] == ajustada
    assert recebidos["glyph"] == ajustada
    # Barras L2/R2 tintadas com o MESMO hex ajustado (helper por widget).
    assert card._l2_bar._hefesto_tint_hex == rgb_para_hex(ajustada)
    assert card._r2_bar._hefesto_tint_hex == rgb_para_hex(ajustada)


def test_sem_cor_conhecida_accent_neutro_ajustado_nos_widgets(
    host: _Host,
) -> None:
    host._render_live_state(
        _state(_entry(lightbar_rgb=None, lightbar_source="desconhecida"))
    )
    card = host.cards()[0]
    neutro_ajustado = ensure_min_contrast(ACCENT_NEUTRO)
    assert card._accent == neutro_ajustado
    assert card._l2_bar._hefesto_tint_hex == rgb_para_hex(neutro_ajustado)


# ---------------------------------------------------------------------------
# Frame Estado: a bateria do primário some com 2+ (cada card tem a sua)
# ---------------------------------------------------------------------------


def test_bateria_do_frame_estado_some_com_dois_ou_mais(host: _Host) -> None:
    state = _state(
        _entry(),
        _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
    )
    host._render_slow_state(state)
    assert host.builder.get_object("status_battery_bar").visible is False
    assert host.builder.get_object("status_battery_caption").visible is False


def test_bateria_do_frame_estado_fica_com_um_controle_sem_sufixo(
    host: _Host,
) -> None:
    host._render_slow_state(_state(_entry()))
    bar = host.builder.get_object("status_battery_bar")
    assert bar.visible is True
    assert bar.text == "80 %"
    assert "Controle 1" not in (bar.text or "")


def test_render_offline_limpa_os_cards_e_restaura_a_bateria(
    host: _Host,
) -> None:
    host._render_live_state(
        _state(
            _entry(),
            _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
        )
    )
    assert len(host.cards()) == 2

    host._render_offline()

    assert host.cards() == []
    assert host._status_cards == {}
    assert host.builder.get_object("status_battery_bar").visible is True


# ---------------------------------------------------------------------------
# Gate de timers — diff contra o baseline da mixin (aceite do STATUS-02)
# ---------------------------------------------------------------------------


def test_gate_timers_nenhuma_ocorrencia_nova_vs_baseline() -> None:
    """Baseline da mixin: 2 periódicos em ms + 1 periódico em segundos +
    1 one-shot de 5 s (ambos via timeout_add_seconds) + 2 idle one-shot.
    O card NÃO agenda nada. Qualquer timer novo estoura este diff.
    """
    src_mixin = Path(sa_mod.__file__).read_text(encoding="utf-8")
    src_card = Path(cc_mod.__file__).read_text(encoding="utf-8")

    assert len(re.findall(r"GLib\.timeout_add\(", src_mixin)) == 2
    assert len(re.findall(r"GLib\.timeout_add_seconds\(", src_mixin)) == 2
    assert len(re.findall(r"GLib\.idle_add\(", src_mixin)) == 2

    assert re.search(r"GLib\.(timeout_add|idle_add)", src_card) is None
    assert "from gi.repository import Gtk" in src_card  # sem GLib no card


# ---------------------------------------------------------------------------
# Tamanho dos sticks: 90px com 2+ cards, 120px com 1 (layout equivalente)
# ---------------------------------------------------------------------------


def test_sticks_90px_com_dois_cards_e_120px_com_um(host: _Host) -> None:
    host._render_live_state(_state(_entry()))
    card_solo = host.cards()[0]
    largura, altura = card_solo._stick_left.get_size_request()
    assert (largura, altura) == (120, 120)

    host._render_live_state(
        _state(
            _entry(),
            _entry(index=1, uniq="aa:bb:cc:00:00:02", is_primary=False),
        )
    )
    for card in host.cards():
        largura, altura = card._stick_left.get_size_request()
        assert (largura, altura) == (90, 90)


def test_swatch_guarda_a_cor_crua_nao_a_ajustada(host: _Host) -> None:
    """D8: o swatch é a identidade CRUA; só os traços recebem a ajustada."""
    host._render_live_state(_state(_entry(lightbar_rgb=list(COR_A))))
    card = host.cards()[0]
    assert card._swatch_rgb == COR_A
    assert card._accent == ensure_min_contrast(COR_A)
    assert card._swatch_rgb != card._accent  # 16,32,72 é ilegível cru (1.12:1)
