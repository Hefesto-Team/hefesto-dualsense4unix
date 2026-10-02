"""Cards de controle da aba Início (FEAT-STATE-PER-CONTROLLER-01 + LEIGO-02)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_controller_cards: importa código da janela GTK")

import sys
import types
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.app.actions.home_actions import _flavor_label, _mode_label


class TestLabelsDosToasts:
    """LEIGO-02: os toasts falam o rótulo do botão, nunca o id interno."""

    def test_modo_vira_o_texto_do_botao(self) -> None:
        assert _mode_label("gamepad") == "Jogar pelo Hefesto"
        assert _mode_label("desktop") == "Controlar o PC"
        assert _mode_label("native") == "Conexão Nativa (Sony)"

    def test_aparencia_vira_o_texto_do_botao(self) -> None:
        assert _flavor_label("xbox") == "Xbox 360"
        assert _flavor_label("dualsense") == "DualSense (botões PlayStation)"

    def test_id_desconhecido_nao_vira_vazio(self) -> None:
        """Daemon mais novo com um modo que esta GUI não conhece: mostra o id"""
        assert _mode_label("modo_do_futuro") == "modo_do_futuro"
        assert _flavor_label(None) == "None"

    def test_nenhum_rotulo_promete_vibracao_exclusiva(self) -> None:
        """O vpad uhid (SPRINT-UHID-VPAD-01) fez a máscara DualSense vibrar —
        "(vibra)"/"(sem vibrar)" viraram mentira e não podem voltar."""
        for texto in (_flavor_label("xbox"), _flavor_label("dualsense")):
            assert "vibra" not in texto.lower()


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


