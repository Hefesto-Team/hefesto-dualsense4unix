"""GATILHOS-APLICADO-COM-PROVA/T8 — ler a frase de um modo custa ZERO byte.

O DEFEITO
=========
Os 19 modos de gatilho **têm** descrição, e ela aparece — para **um** modo por
vez, o selecionado (``_rebuild_params`` escreve em ``trigger_<side>_desc``).
Para ler a de outro é preciso CLICAR nele, e clicar agenda um ``trigger.set``
300 ms depois (``_schedule_live_preview``). São 38 botões na tela, uma frase
visível, e comparar seis modos parecidos custava seis aplicações no controle de
alguém — com a trava manual armada a cada uma delas
(``daemon/ipc_handlers._handle_trigger_set`` -> ``mark_manual_trigger_active``),
o que pausa a troca automática de perfil.

A CURA, E POR QUE ELA É UMA LINHA E MEIA
========================================
O mecanismo de dica por botão já existia e já tinha quatro chamadores de
produção (``app/widgets/segmented_selector.set_tooltips``, usado por
``secao_orcamento``, ``controller_card``, ``profiles_actions`` e
``external_card``). A aba com MAIS botões do produto era a única que não o
chamava.

A FONTE É O ``PRESETS``, E ISSO É O QUE ESTE ARQUIVO PRENDE
===========================================================
Uma cópia dos 19 textos seria um SEGUNDO dono dos rótulos — e é assim que as
duas versões divergem sem ninguém ver. As duas pontas do teste estão presas na
mesma fonte de propósito: arrancar o ``set_tooltips`` reprova, e mexer numa
``description`` do ``PRESETS`` reprova **o mesmo teste**, porque ele compara com
o que o ``PRESETS`` diz AGORA, nunca com um literal daqui.

O TEXTO NÃO É NOVO
==================
É a mesma frase que a aba já mostra para o modo selecionado — é o que mantém a
T8 na classe **cosmética pré-aprovada** ("tornar dica visível"). Reescrever
qualquer uma das 19 a tornaria estrutural e faria esperar o olho dela; por isso
o teste também exige que nenhuma delas seja escrita à mão neste arquivo nem no
módulo da aba.

GTK REAL, SEM JANELA NA TELA DELA
=================================
Os botões são ``Gtk.RadioButton`` de verdade, criados fora de qualquer
toplevel: nada é mapeado, nada aparece. É o que permite ler
``get_tooltip_text()`` do BOTÃO — a pergunta certa é o que o dedo dela alcança,
não o que um dicionário guardou.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("as dicas dos dezenove modos de gatilho")

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import triggers_actions
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS, TriggerParamSpec
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin


class _Host(TriggersActionsMixin):
    """Monta a aba pelo MÉTODO DE PRODUÇÃO, com widgets GTK de verdade."""

    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {}
        for lado in ("left", "right"):
            self._widgets[f"trigger_{lado}_mode_slot"] = Gtk.Box()
            self._widgets[f"trigger_{lado}_preset_slot"] = Gtk.Box()
            self._widgets[f"trigger_{lado}_preset_row"] = Gtk.Box()
            self._widgets[f"trigger_{lado}_params_box"] = Gtk.Box()
            self._widgets[f"trigger_{lado}_desc"] = Gtk.Label()

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)


def _dicas_dos_botoes(host: _Host, side: str) -> dict[str, str | None]:
    """``{id do modo: tooltip que está NO BOTÃO}`` — lido do widget."""
    sel = host._trigger_mode[side]
    return {
        the_id: botao.get_tooltip_text()
        for (the_id, _label), botao in zip(sel._items, sel._buttons, strict=True)
    }


class TestCadaModoExplicaSeSemSerClicado:
    def test_os_dezenove_botoes_carregam_a_descricao_do_presets(self) -> None:
        host = _Host()
        host.install_triggers_tab()
        esperado = {spec.name: spec.description for spec in PRESETS}
        assert len(esperado) == 19
        for side in ("left", "right"):
            assert _dicas_dos_botoes(host, side) == esperado, (
                f"lado {side}: a dica do botão não é a `description` do PRESETS"
            )

    def test_nenhum_modo_fica_sem_dica(self) -> None:
        """38 botões, 38 dicas — a conta que a sprint mediu ao contrário."""
        host = _Host()
        host.install_triggers_tab()
        vazias = [
            the_id
            for side in ("left", "right")
            for the_id, dica in _dicas_dos_botoes(host, side).items()
            if not dica
        ]
        assert vazias == [], f"modos sem dica no botão: {vazias}"

    def test_a_dica_do_botao_e_a_mesma_frase_que_a_aba_ja_mostrava(self) -> None:
        """Texto NOVO tornaria a T8 estrutural. Este teste é o que garante que não.

        `_rebuild_params` escreve `<i>{spec.description}</i>` no rótulo de
        descrição do lado. A dica tem de sair da MESMA string — se um dia
        alguém reescrever uma das 19 só para a dica, as duas divergem e isto
        reprova.
        """
        host = _Host()
        host.install_triggers_tab()
        rotulo = host._get("trigger_left_desc")
        dicas = _dicas_dos_botoes(host, "left")
        for spec in PRESETS:
            host._rebuild_params("left", spec.name)
            assert rotulo.get_text() == spec.description
            assert dicas[spec.name] == spec.description


class TestAFonteEUmaSo:
    def test_a_aba_monta_as_dicas_a_partir_do_presets(self) -> None:
        """A mordida gêmea: uma CÓPIA dos 19 textos passaria no teste de cima."""
        import inspect

        fonte = "\n".join(
            linha
            for linha in inspect.getsource(
                TriggersActionsMixin.install_triggers_tab
            ).splitlines()
            if not linha.lstrip().startswith("#")
        )
        assert "set_tooltips" in fonte, "a aba deixou de pedir as dicas"
        assert "spec.description for spec in PRESETS" in fonte, (
            "as dicas passaram a sair de outro lugar que não o `PRESETS`"
        )

    def test_nenhuma_das_dezenove_frases_esta_escrita_na_aba(self) -> None:
        """Se uma delas aparecer como literal em `triggers_actions.py`, virou"""
        from pathlib import Path

        fonte = Path(triggers_actions.__file__).read_text(encoding="utf-8")
        repetidas = [s.name for s in PRESETS if s.description and s.description in fonte]
        assert repetidas == [], f"descrição copiada para a aba: {repetidas}"


class TestOCampoMortoSaiu:
    """A metade da T8 que era DECISÃO, e a decisão foi tirar."""

    def test_o_help_text_nao_existe_mais(self) -> None:
        assert not hasattr(TriggerParamSpec("x", "X", 0, 1), "help_text")

    def test_e_a_conta_que_o_motivou_continua_a_mesma(self) -> None:
        """73 parâmetros — o número que a medição da sprint corrigiu (não 38)."""
        assert sum(len(spec.params) for spec in PRESETS) == 73

    def test_o_rotulo_do_slider_continua_com_a_dica_que_ele_tinha(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        host = _Host()
        host.install_triggers_tab()
        spec = triggers_actions.get_spec("Bow")
        assert spec is not None
        linha = host._build_param_row(spec.params[0])
        rotulo = linha.get_children()[0]
        assert rotulo.get_tooltip_text() == spec.params[0].label
