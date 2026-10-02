"""§P9 — o que esta aba esconde volta sozinho no próximo `show_all()` da janela."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p9: o que a aba escondeu volta")

from typing import Any

from hefesto_dualsense4unix.app.actions import profiles_actions as pa


class _Widget:
    """Um widget do GTK no que interessa a este teste: `no_show_all` manda."""

    def __init__(self, no_show_all: bool = True) -> None:
        self.no_show_all = no_show_all
        self.visivel = False
        self.filhos: list[Any] = []

    def set_no_show_all(self, valor: bool) -> None:
        self.no_show_all = bool(valor)

    def show_all(self) -> None:
        """A doutrina: `no_show_all` armado faz o `show_all()` PULAR o widget."""
        if self.no_show_all:
            return
        self.visivel = True
        for filho in self.filhos:
            filho.show_all()

    def hide(self) -> None:
        self.visivel = False

    def set_visible(self, v: bool) -> None:
        self.visivel = bool(v)

    def get_children(self) -> list[Any]:
        return list(self.filhos)

    def remove(self, filho: Any) -> None:
        self.filhos.remove(filho)

    def destroy(self) -> None:
        return None

    def pack_start(self, filho: Any, *_a: Any) -> None:
        self.filhos.append(filho)

    def set_markup(self, _m: str) -> None:
        return None

    def set_text(self, _t: str) -> None:
        return None

    def set_tooltip_text(self, _t: str) -> None:
        return None


class _Aba(pa.ProfilesActionsMixin):  # type: ignore[misc]
    """A aba com os três widgets escondíveis, e nada mais."""

    def __init__(self) -> None:
        self.caixa = _Widget()
        self.outros = _Widget()
        self.exigencia = _Widget()
        self._widgets: dict[str, Any] = {
            "profile_steam_input_box": self.caixa,
            "profile_steam_input_outros": self.outros,
            "profile_exigencia_invisivel": self.exigencia,
        }
        self._regra_do_disco = None
        self._estado_do_radio = None
        self._aviso_do_radio_fragil = _Widget()
        self._mode_gamepad_opts = None
        self._mode_kind_selector = None
        self.buscou_carimbo = 0

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _sincronizar_caixa_do_steam_input(self) -> None:
        return None

    def _buscar_as_pontes_confirmadas(self) -> None:
        self.buscou_carimbo += 1

    def _appid_do_editor(self) -> str | None:
        return None

    @staticmethod
    def _appids_do_steam_input() -> set[str]:
        return set()


def _a_janela_reaparece(aba: _Aba) -> None:
    """O que `app.py:show_window()` faz: `show_all()` na janela inteira."""
    for widget in (aba.caixa, aba.outros, aba.exigencia, aba._aviso_do_radio_fragil):
        widget.show_all()


class TestACaixinhaDoSteamInputNaoVolta:
    def test_escondida_ela_continua_escondida_depois_da_bandeja(self) -> None:
        """MORDE o rearme: sem ele a caixinha volta sob o 'Aplica a:' errado."""
        aba = _Aba()
        aba._mostrar_caixa_do_steam_input(True)
        assert aba.caixa.visivel is True, "a caixa não apareceu na escolha certa"

        aba._mostrar_caixa_do_steam_input(False)
        _a_janela_reaparece(aba)

        assert aba.caixa.visivel is False

    def test_e_ela_continua_aparecendo_quando_deve(self) -> None:
        """A cura da CAMPO-QUE-NAO-NASCIA-01 não pode ser desfeita por esta."""
        aba = _Aba()
        aba._mostrar_caixa_do_steam_input(True)
        aba._mostrar_caixa_do_steam_input(False)

        aba._mostrar_caixa_do_steam_input(True)

        assert aba.caixa.visivel is True


class TestOsOutrosDoisWidgetsTambem:
    def test_a_lista_vazia_de_outros_nao_volta(self) -> None:
        aba = _Aba()
        aba.outros.set_no_show_all(False)
        aba.outros.visivel = True

        aba._sincronizar_outros_marcados()
        _a_janela_reaparece(aba)

        assert aba.outros.visivel is False

    def test_a_exigencia_invisivel_vazia_nao_volta(self) -> None:
        aba = _Aba()
        aba.exigencia.set_no_show_all(False)
        aba.exigencia.visivel = True

        aba._sincronizar_exigencia_invisivel()
        _a_janela_reaparece(aba)

        assert aba.exigencia.visivel is False

    def test_o_aviso_do_radio_apagado_nao_volta(self) -> None:
        """O §P8 nasceu nesta mesma noite — e nasceu com a cura, não sem."""
        aba = _Aba()
        aba._aviso_do_radio_fragil.set_no_show_all(False)
        aba._aviso_do_radio_fragil.visivel = True

        aba._sincronizar_aviso_do_radio("gamepad")
        _a_janela_reaparece(aba)

        assert aba._aviso_do_radio_fragil.visivel is False
