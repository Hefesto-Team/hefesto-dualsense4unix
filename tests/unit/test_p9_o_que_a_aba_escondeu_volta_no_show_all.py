"""§P9 — o que esta aba esconde volta sozinho no próximo `show_all()` da janela.

MEDIDO em 25/08/2026, e é a correção do mecanismo que a sprint supôs.

**O que a sprint dizia** (PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/9): trocar o
"Aplica a:" de "Jogo da Steam" para "Steam" deixaria a lista de outros marcados
mostrando N-1. **Não reproduz** — e a razão é boa: `profile_steam_input_outros`
é FILHO de `profile_steam_input_box`, e a troca de escolha chama
`_mostrar_caixa_do_steam_input(False)`, que esconde o pai inteiro. A lista
desatualizada existe, e ninguém a vê.

**O que reproduz, e é pior:** o esconder não dura. Os três widgets que esta aba
revela fazem `set_no_show_all(False)` para aparecer — a cura da
CAMPO-QUE-NAO-NASCIA-01 — e **nunca rearmavam** ao esconder. O desarme é
permanente, e `app.py:show_window()`::

    def show_window(self) -> None:
        \"\"\"Traz a janela para a frente (SIGUSR1, tray, notificação).\"\"\"
        ...
        self.window.show_all()

chama `show_all()` na JANELA — o que reexibe todo widget sem `no_show_all`
armado. Resultado, com o gesto mais banal do mundo (escolher "Jogo da Steam",
voltar para "Sempre", e trazer a janela pela bandeja): **a caixinha do Steam
Input reaparece sob um "Aplica a:" que não é jogo da Steam**, com a lista de
outros marcados de outra escolha e um rótulo de exigência vazio.

**O molde certo já estava no mesmo arquivo, uma seção acima:**
`_sync_mode_options_visibility` faz `set_no_show_all(not is_gamepad)` — arma e
desarma. O glade também já dizia a intenção (`no-show-all: True` nos widgets).
Faltava rearmar.

O `_Widget` deste arquivo imita a doutrina do GTK que importa aqui: `show_all()`
IGNORA quem está com `no_show_all` armado, inclusive quando chamado no próprio
widget (é essa a linha que a CAMPO-QUE-NAO-NASCIA-01 documentou).
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.actions import profiles_actions as pa


class _Widget:
    """Um widget do GTK no que interessa a este teste: `no_show_all` manda."""

    def __init__(self, no_show_all: bool = True) -> None:
        self.no_show_all = no_show_all
        self.visivel = False
        self.filhos: list[Any] = []

    # -- a API que o produto usa ------------------------------------------
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

    # A da caixinha não é o objeto deste arquivo; a dos OUTROS é a de
    # verdade, porque o esconder dela é uma das três curas medidas aqui.
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
        """A cura da CAMPO-QUE-NAO-NASCIA-01 não pode ser desfeita por esta.

        Esconder e escolher "Jogo da Steam" de novo tem de revelar a caixa —
        se o rearme ficasse ligado, a caixinha nunca mais apareceria, que é um
        defeito pior que o que este arquivo cura.
        """
        aba = _Aba()
        aba._mostrar_caixa_do_steam_input(True)
        aba._mostrar_caixa_do_steam_input(False)

        aba._mostrar_caixa_do_steam_input(True)

        assert aba.caixa.visivel is True


class TestOsOutrosDoisWidgetsTambem:
    def test_a_lista_vazia_de_outros_nao_volta(self) -> None:
        aba = _Aba()
        aba.outros.set_no_show_all(False)  # como fica depois de uma vez cheia
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
