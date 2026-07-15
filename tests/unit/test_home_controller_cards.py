"""Cards de controle da aba Início (FEAT-STATE-PER-CONTROLLER-01 + LEIGO-02).

Duas camadas, ambas herméticas (sem GTK real):

1. Funções puras de formatação (`_format_controller_subtitle`,
   `_format_controller_title`, `_format_players_hint`, `_mode_label`) — o
   contrato de texto dos cards e dos toasts.
2. `_render_home_controllers` com um Gtk fake injetado em ``sys.modules``
   (o método importa ``gi.repository`` dentro da função, então o
   ``monkeypatch.setitem`` cobre com ou sem PyGObject instalado — A-12).

Os handlers do SegmentedSelector (BUG-HOME-SEGMENTED-SIGNATURE-01) NÃO são
tocados aqui — seguem cobertos por ``test_home_actions_handlers.py``.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import (
    HomeActionsMixin,
    _flavor_label,
    _format_controller_subtitle,
    _format_controller_title,
    _format_players_hint,
    _mode_label,
)

# ---------------------------------------------------------------------------
# 1. Funções puras de formatação
# ---------------------------------------------------------------------------


class TestFormatSubtitle:
    def test_com_bateria_e_primario(self) -> None:
        assert (
            _format_controller_subtitle("usb", is_primary=True, battery_pct=87)
            == "USB  ·  primário  ·  87%"
        )

    def test_sem_bateria_omite_percentual(self) -> None:
        assert (
            _format_controller_subtitle("bt", is_primary=False, battery_pct=None)
            == "BT"
        )

    def test_bateria_zero_e_mostrada(self) -> None:
        """0% é dado REAL (bateria morta) — diferente de None (sem dado)."""
        assert (
            _format_controller_subtitle("bt", is_primary=False, battery_pct=0)
            == "BT  ·  0%"
        )

    def test_bool_nao_vira_bateria(self) -> None:
        """bool é subclasse de int — payload malformado não vira "True%"."""
        assert (
            _format_controller_subtitle("usb", is_primary=False, battery_pct=True)
            == "USB"
        )

    def test_transport_ausente_vira_interrogacao(self) -> None:
        assert (
            _format_controller_subtitle(None, is_primary=False, battery_pct=None)
            == "?"
        )


class TestLabelsDosToasts:
    """LEIGO-02: os toasts falam o rótulo do botão, nunca o id interno."""

    def test_modo_vira_o_texto_do_botao(self) -> None:
        assert _mode_label("gamepad") == "Jogar pelo Hefesto"
        assert _mode_label("desktop") == "Controlar o PC"
        assert _mode_label("native") == "Jogar direto (Sony)"

    def test_aparencia_vira_o_texto_do_botao(self) -> None:
        assert _flavor_label("xbox") == "Xbox 360"
        assert _flavor_label("dualsense") == "DualSense (botões PlayStation)"

    def test_id_desconhecido_nao_vira_vazio(self) -> None:
        """Daemon mais novo com um modo que esta GUI não conhece: mostra o id
        cru em vez de um toast em branco."""
        assert _mode_label("modo_do_futuro") == "modo_do_futuro"
        assert _flavor_label(None) == "None"

    def test_nenhum_rotulo_promete_vibracao_exclusiva(self) -> None:
        """O vpad uhid (SPRINT-UHID-VPAD-01) fez a máscara DualSense vibrar —
        "(vibra)"/"(sem vibrar)" viraram mentira e não podem voltar."""
        for texto in (_flavor_label("xbox"), _flavor_label("dualsense")):
            assert "vibra" not in texto.lower()


class TestFormatControllerTitle:
    """LEIGO-01b: o "P" do card é o número do daemon, nunca a posição na lista."""

    def test_posicao_e_jogador_podem_divergir(self) -> None:
        # 2º controle da lista sendo o jogador 3 é real: índices são reusados
        # quando um jogador sai e outro entra.
        assert _format_controller_title(2, 3) == "Controle 2 — P3"

    def test_sem_numero_de_jogador_o_card_so_se_identifica(self) -> None:
        """Modo desktop/nativo, ou jogador ainda subindo: não inventa um "P"."""
        assert _format_controller_title(1, None) == "Controle 1"

    def test_bool_nao_vira_numero_de_jogador(self) -> None:
        assert _format_controller_title(1, True) == "Controle 1"


class TestFormatPlayersHint:
    """LEIGO-01: a frase que substituiu o checkbox de co-op."""

    def test_dois_controles_dois_jogadores(self) -> None:
        assert (
            _format_players_hint([{"player": 1}, {"player": 2}])
            == "2 controles = 2 jogadores"
        )

    def test_um_controle_nao_diz_nada(self) -> None:
        """Com um controle só não há pergunta a responder."""
        assert _format_players_hint([{"player": 1}]) == ""
        assert _format_players_hint([]) == ""

    def test_nao_promete_jogadores_que_o_jogo_ainda_nao_ve(self) -> None:
        """2 controles alimentando o MESMO vpad não são 2 jogadores."""
        assert _format_players_hint([{"player": 1}, {"player": 1}]) == ""

    def test_jogador_ainda_subindo_nao_conta(self) -> None:
        assert _format_players_hint([{"player": 1}, {"player": None}]) == ""

    def test_quatro_jogadores(self) -> None:
        assert (
            _format_players_hint([{"player": n} for n in (1, 2, 3, 4)])
            == "4 controles = 4 jogadores"
        )


# ---------------------------------------------------------------------------
# 2. Render dos cards com Gtk fake
# ---------------------------------------------------------------------------


class _StyleCtx:
    def __init__(self) -> None:
        self.classes: list[str] = []

    def add_class(self, name: str) -> None:
        self.classes.append(name)


class _FakeWidget:
    """Cobre o subconjunto de Gtk.Label/Gtk.Box usado pelo render dos cards."""

    def __init__(
        self,
        label: str | None = None,
        orientation: object = None,
        spacing: int | None = None,
    ) -> None:
        self.label = label
        self.children: list[_FakeWidget] = []
        self.style = _StyleCtx()

    def get_style_context(self) -> _StyleCtx:
        return self.style

    def set_xalign(self, value: float) -> None:
        pass

    def set_margin_end(self, value: int) -> None:
        pass

    def set_markup(self, markup: str) -> None:
        self.label = markup

    def pack_start(self, child: _FakeWidget, *args: object) -> None:
        self.children.append(child)

    def get_children(self) -> list[_FakeWidget]:
        return list(self.children)

    def remove(self, child: _FakeWidget) -> None:
        self.children.remove(child)

    def show_all(self) -> None:
        pass


class _Host:
    """Instância mínima com o que `_render_home_controllers` toca."""

    _render_home_controllers = HomeActionsMixin._render_home_controllers

    def __init__(self) -> None:
        self._home_controllers_box = _FakeWidget()


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gtk fake em ``sys.modules`` — o import local do render cai nele."""
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_FakeWidget,
        Box=_FakeWidget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _card_texts(card: _FakeWidget) -> list[str]:
    return [str(child.label) for child in card.children]


def test_render_mostra_bateria_e_nunca_o_mac(fake_gtk: None) -> None:
    """LEIGO-02: o fim do MAC saiu do card — a bateria e o jogador ficam.

    O hash não casa com nada que ela consiga ler no controle físico; quem
    distingue os aparelhos na mesa é a cor da luz e o LED de jogador.
    """
    host = _Host()
    controllers: list[dict[str, Any]] = [
        {
            "index": 0,
            "connected": True,
            "transport": "usb",
            "is_primary": True,
            "uniq": "a0ab51c311f0",
            "battery_pct": 87,
        },
        {
            "index": 1,
            "connected": True,
            "transport": "bt",
            "is_primary": False,
            "uniq": None,
            "battery_pct": None,
        },
    ]

    host._render_home_controllers(controllers)

    cards = host._home_controllers_box.get_children()
    assert len(cards) == 2

    texts_p1 = _card_texts(cards[0])
    assert "USB  ·  primário  ·  87%" in texts_p1
    assert not any("c311f0" in t for t in texts_p1), (
        "o fim do MAC voltou ao card — ele não identifica nada que a usuária "
        "consiga ler no controle"
    )

    texts_p2 = _card_texts(cards[1])
    assert "BT" in texts_p2
    # Sem bateria: nada de "%" no segundo card.
    assert not any("%" in t for t in texts_p2)


def test_render_sem_campos_novos_nao_regride(fake_gtk: None) -> None:
    """Payload antigo (daemon velho, sem uniq/battery_pct) segue renderizando."""
    host = _Host()
    host._render_home_controllers(
        [{"index": 0, "connected": True, "transport": "usb", "is_primary": True}]
    )

    (card,) = host._home_controllers_box.get_children()
    assert "USB  ·  primário" in _card_texts(card)


def test_render_usa_o_jogador_do_daemon_e_nao_a_posicao(fake_gtk: None) -> None:
    """LEIGO-01b: com índice reusado, o card do 2º da lista mostra P3."""
    host = _Host()
    host._render_home_controllers(
        [
            {"index": 0, "connected": True, "transport": "usb",
             "is_primary": True, "player": 1},
            {"index": 1, "connected": True, "transport": "bt",
             "is_primary": False, "player": 3},
        ]
    )

    cards = host._home_controllers_box.get_children()
    assert "<b>Controle 1 — P1</b>" in _card_texts(cards[0])
    assert "Controle 2 — P3" in _card_texts(cards[1])


def test_render_sem_jogador_omite_o_p(fake_gtk: None) -> None:
    """Modo desktop: ninguém é jogador — o card não inventa P1."""
    host = _Host()
    host._render_home_controllers(
        [{"index": 0, "connected": True, "transport": "usb",
          "is_primary": True, "player": None}]
    )

    (card,) = host._home_controllers_box.get_children()
    assert "<b>Controle 1</b>" in _card_texts(card)


def test_render_lista_vazia_mostra_placeholder(fake_gtk: None) -> None:
    host = _Host()
    host._render_home_controllers([])

    (placeholder,) = host._home_controllers_box.get_children()
    assert placeholder.label == "Nenhum controle conectado."
