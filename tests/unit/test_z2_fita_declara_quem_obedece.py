"""Z2-8 — a fita para de mandar em quem não a obedece.

24/08/2026. M3 (censo da sprint ONDA0-Z2): a fita "Ajustes vão para:
[1][2][3][4]" mora no ``header_bar``, global à janela — e só UMA das onze
abas a esmaecia de propósito (Configurações, ``set_alvo_inativo``). Nas
outras seis que não leem o alvo (Início, No jogo, Perfis, Sistema, Emulação,
Navegação) a fita ficava acesa e sensível sem que nada nelas a obedecesse.

Estes testes trancam o mapa ``HefestoApp._ALVO_POR_ABA`` que generaliza o
mecanismo: cada aba do mapa que NÃO lê o alvo esmaece com o motivo dela
(nunca pintado — Z2-5); as quatro que leem (Status, Gatilhos, Lightbar,
Rumble) ficam sensíveis.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("z2 fita declara quem obedece")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
pytest.importorskip(
    "gi.repository.GdkPixbuf", reason="precisa da typelib GdkPixbuf"
)
from gi.repository import Gtk

from hefesto_dualsense4unix.app.app import HefestoApp

#: As quatro abas leitoras de hoje (M3 do censo) e as sete inertes — a
#: lista É o contrato: acrescentar uma leitora move a linha dela para cá.
ABAS_LEITORAS = (
    "tab_status_box",
    "tab_triggers_box",
    "tab_lightbar_box",
    "tab_rumble_box",
)
ABAS_INERTES = (
    "tab_home_box",
    "tab_no_jogo_box",
    "profiles_paned",
    "daemon_box",
    "emulation_box",
    "tab_navegacao_dsx",
    "tab_config_box",
)


class _AppFalso:
    """Só o suficiente para exercitar `_on_notebook_switch_page` sem GUI real."""

    _REFRESH_POR_ABA = HefestoApp._REFRESH_POR_ABA
    _ABA_STATUS = HefestoApp._ABA_STATUS
    _ALVO_POR_ABA = HefestoApp._ALVO_POR_ABA
    _MOTIVO_ALVO_AINDA_NAO_LIGADO = HefestoApp._MOTIVO_ALVO_AINDA_NAO_LIGADO
    _on_notebook_switch_page = HefestoApp._on_notebook_switch_page

    def __init__(self) -> None:
        self.chamadas_inativar: list[tuple[bool, str]] = []
        for nomes in self._REFRESH_POR_ABA.values():
            for nome in nomes:
                setattr(self, nome, lambda: None)

    def set_alvo_inativo(self, inativo: bool, motivo: str = "") -> None:
        self.chamadas_inativar.append((inativo, motivo))


def _pagina(nome: str) -> Gtk.Widget:
    page = Gtk.Box()
    Gtk.Buildable.set_name(page, nome)
    return page


@pytest.mark.parametrize("aba", ABAS_LEITORAS)
def test_aba_leitora_fica_sensivel(aba: str) -> None:
    app = _AppFalso()
    app._on_notebook_switch_page(None, _pagina(aba), 0)
    assert app.chamadas_inativar == [(False, "")], (
        f"{aba} lê o alvo e a fita continuou/ficou insensível"
    )


@pytest.mark.parametrize("aba", ABAS_INERTES)
def test_aba_inerte_esmaece_com_motivo(aba: str) -> None:
    """A MORDIDA: as seis abas que não liam nada agora esmaecem — com
    motivo guardado, nunca pintado (Z2-5)."""
    app = _AppFalso()
    app._on_notebook_switch_page(None, _pagina(aba), 0)
    assert len(app.chamadas_inativar) == 1
    inativo, motivo = app.chamadas_inativar[0]
    assert inativo is True, f"{aba} não lê o alvo e a fita ficou sensível"
    assert motivo, f"{aba} esmaeceu sem motivo — Z2-5 exige o texto"


def test_ida_e_volta_lightbar_para_perfis() -> None:
    """O caso do aceite: Perfis insensível, Lightbar sensível, no MESMO app."""
    app = _AppFalso()

    app._on_notebook_switch_page(None, _pagina("profiles_paned"), 0)
    app._on_notebook_switch_page(None, _pagina("tab_lightbar_box"), 0)

    assert app.chamadas_inativar[-2] == (
        True,
        HefestoApp._MOTIVO_ALVO_AINDA_NAO_LIGADO,
    )
    assert app.chamadas_inativar[-1] == (False, "")


def test_aba_fora_do_mapa_esmaece_por_seguranca_e_nao_crasha() -> None:
    """Runtime não pode ficar sensível por omissão — quem reprova a
    ausência na FONTE é o portão da Z2-9, não o usuário na tela."""
    app = _AppFalso()
    app._on_notebook_switch_page(None, _pagina("aba_que_nao_existe_no_mapa"), 0)
    assert app.chamadas_inativar == [
        (True, HefestoApp._MOTIVO_ALVO_AINDA_NAO_LIGADO)
    ]


def test_tirar_uma_aba_do_mapa_reprova_nomeando_a_aba() -> None:
    """O molde do `_REFRESH_POR_ABA` da Z5: o mapa cobre as ONZE abas."""
    todas = set(ABAS_LEITORAS) | set(ABAS_INERTES)
    faltando = todas - set(HefestoApp._ALVO_POR_ABA)
    assert not faltando, f"abas fora de `_ALVO_POR_ABA`: {sorted(faltando)}"
