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


import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions import triggers_actions
from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS, TriggerParamSpec


class TestAFonteEUmaSo:

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

